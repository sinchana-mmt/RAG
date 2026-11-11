"""Load atomic case-level FAQ chunks. One case = one retrieval document."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "data" / "digitrail_faq_cases.json"


def case_to_chunk(case: dict[str, Any]) -> str:
    steps = "\n".join(case["what_to_do"])
    messages = "\n".join(f"- {m}" for m in case.get("exact_messages", []))
    return (
        f"CASE {case['case_id']} {case['title']}\n"
        f"Section: {case['section']}\n"
        f"Screen: {case['screen']}\n"
        f"Exact messages / what you see:\n{messages}\n"
        f"SCENARIO\n{case['scenario']}\n"
        f"WHAT YOU SEE\n{case['what_you_see']}\n"
        f"WHAT IT MEANS\n{case['what_it_means']}\n"
        f"WHAT TO DO\n{steps}\n"
        f"PASS WHEN\n{case['pass_when']}\n"
        f"ESCALATE WHEN\n{case['escalate_when']}\n"
    )


def searchable_text(case: dict[str, Any]) -> str:
    """BM25/embedding text: IDs, titles, and exact on-screen sentences first."""
    messages = " ".join(case.get("exact_messages", []))
    steps = " ".join(case["what_to_do"])
    return (
        f"Case {case['case_id']} CASE {case['case_id']} {case['title']} "
        f"{case['section']} {case['screen']} {messages} {case['what_you_see']} "
        f"{case['scenario']} {case['what_it_means']} {steps} "
        f"{case['pass_when']} {case['escalate_when']}"
    )


@lru_cache(maxsize=1)
def load_faq() -> dict[str, Any]:
    with CASES_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    for case in data["cases"]:
        case["chunk"] = case_to_chunk(case)
        case["search_text"] = searchable_text(case)
    return data


def all_cases() -> list[dict[str, Any]]:
    return load_faq()["cases"]


def case_by_number(number: int) -> dict[str, Any] | None:
    for case in all_cases():
        if int(case["case_number"]) == number:
            return case
    return None


def not_found_protocol() -> str:
    return load_faq()["not_found_protocol"]
