"""Map a retrieved FAQ case onto the mandatory operator response format."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

from knowledge import not_found_protocol
from prompt import (
    DOCUMENT_DATE,
    DOCUMENT_ID,
    NOT_FOUND_ANSWER,
    REVISION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from retriever import get_retriever

load_dotenv()


def format_case_answer(case: dict[str, Any]) -> str:
    steps = "\n".join(
        step if step[:1].isdigit() else f"{i}. {step}"
        for i, step in enumerate(case["what_to_do"], start=1)
    )
    return (
        f"* **Matching Case Number & Title:** Case {case['case_id']}: {case['title']}\n"
        f"* **What It Means:** {case['what_it_means']}\n"
        f"* **What To Do:**\n{steps}\n"
        f"* **Pass Condition:** {case['pass_when']}\n"
        f"* **Escalate When:** {case['escalate_when']}"
    )


def format_not_found() -> str:
    protocol = not_found_protocol()
    return (
        NOT_FOUND_ANSWER
        + "\n\nOfficial closing rule: "
        + protocol
    )


def _llm_enabled() -> bool:
    azure = bool(
        os.getenv("AZURE_OPENAI_API_KEY")
        and os.getenv("AZURE_OPENAI_ENDPOINT")
        and os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    )
    openai = bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL"))
    return azure or openai


def _chat_client_and_model():
    """Azure OpenAI (inward service) wins when those variables are set."""
    temperature = float(os.getenv("LLM_TEMPERATURE", "0"))
    if os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT"):
        from openai import AzureOpenAI

        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        )
        model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")
        return client, model, temperature

    from openai import OpenAI

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )
    return client, os.getenv("OPENAI_MODEL", ""), temperature


def _llm_format(question: str, cases: list[dict[str, Any]]) -> str | None:
    """Optional temperature=0 copy-and-format pass. Falls back on any failure."""
    if not _llm_enabled():
        return None
    try:
        context = "\n\n-----\n\n".join(c["chunk"] for c in cases)
        client, model, temperature = _chat_client_and_model()
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(question, context)},
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        return text or None
    except Exception:
        return None


def to_public_case(case: dict[str, Any] | None) -> dict[str, Any] | None:
    if not case:
        return None
    return {
        "case_id": case["case_id"],
        "title": case["title"],
        "section": case["section"],
        "screen": case["screen"],
        "exact_messages": case.get("exact_messages", []),
        "what_it_means": case["what_it_means"],
        "what_to_do": case["what_to_do"],
        "pass_condition": case["pass_when"],
        "escalate_when": case["escalate_when"],
        "score": case.get("score"),
    }


def answer_question(question: str, top_k: int = 3) -> dict[str, Any]:
    retriever = get_retriever()
    hits = retriever.search(question, top_k=top_k)
    if not hits:
        return {
            "found": False,
            "answer": format_not_found(),
            "cases": [],
            "source": "faq-not-found",
            "document": f"{DOCUMENT_ID} Revision {REVISION} ({DOCUMENT_DATE})",
        }

    llm_text = _llm_format(question, hits)
    return {
        "found": True,
        "answer": llm_text or format_case_answer(hits[0]),
        "cases": hits,
        "source": "llm-copy" if llm_text else "faq-template",
        "document": f"{DOCUMENT_ID} Revision {REVISION} ({DOCUMENT_DATE})",
    }
