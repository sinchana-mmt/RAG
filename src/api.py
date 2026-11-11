"""FAQ fetch API for the DigiTrail client and gateway.

The React client calls the gateway at VITE_API_BASE_URL (http://localhost:7002/v1).
Point the gateway at this service:

    FAQ_SERVICE_URL=http://127.0.0.1:7010

and proxy /v1/faq to that host. This process does not replace inward (Azure OCR),
the user service on 7003, or the incoming service on 7009.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from answer import answer_question, to_public_case
from knowledge import all_cases, load_faq
from prompt import DOCUMENT_DATE, DOCUMENT_ID, REVISION

load_dotenv()

app = FastAPI(
    title="DigiTrail Known Issues FAQ",
    version=f"{DOCUMENT_ID}-rev-{REVISION}",
    description="Grounded fetch API for DT-FAQ-001. Answers only from the official cases.",
)

origins = [
    origin.strip()
    for origin in os.getenv("CORS_URLS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Exact sentence on the DigiTrail screen")
    top_k: int = Field(3, ge=1, le=5)


@app.get("/health")
def health() -> dict:
    faq = load_faq()["document"]
    return {
        "status": "ok",
        "document": faq["id"],
        "revision": faq["revision"],
        "date": faq["date"],
        "cases": faq["case_count"],
        "endpoints": [
            "GET /health",
            "GET /v1/faq/cases",
            "GET /v1/faq/cases/{case_id}",
            "POST /v1/faq/ask",
        ],
    }


def list_cases() -> dict:
    return {
        "document": f"{DOCUMENT_ID} Revision {REVISION} ({DOCUMENT_DATE})",
        "cases": [
            {
                "case_id": case["case_id"],
                "title": case["title"],
                "section": case["section"],
                "screen": case["screen"],
                "exact_messages": case.get("exact_messages", []),
            }
            for case in all_cases()
        ],
    }


def get_case(case_id: str) -> dict:
    wanted = case_id.zfill(2)
    for case in all_cases():
        if case["case_id"] == wanted:
            public = to_public_case(case)
            assert public is not None
            return public
    raise HTTPException(status_code=404, detail=f"Case {wanted} is not in {DOCUMENT_ID}")


def ask(body: AskRequest) -> dict:
    result = answer_question(body.question.strip(), top_k=body.top_k)
    primary = to_public_case(result["cases"][0]) if result["cases"] else None
    return {
        "found": result["found"],
        "document": result["document"],
        "source": result["source"],
        "answer": result["answer"],
        "case": primary,
        "alternates": [to_public_case(case) for case in result["cases"][1:]],
    }


# Client base is http://localhost:7002/v1, so the gateway forwards /faq/*.
# Direct calls use /v1/faq/* on this process.
for _prefix in ("/v1/faq", "/faq"):
    app.add_api_route(f"{_prefix}/cases", list_cases, methods=["GET"])
    app.add_api_route(f"{_prefix}/cases/{{case_id}}", get_case, methods=["GET"])
    app.add_api_route(f"{_prefix}/ask", ask, methods=["POST"])


def main() -> None:
    import uvicorn

    host = os.getenv("FAQ_API_HOST", "127.0.0.1")
    port = int(os.getenv("FAQ_API_PORT", "7010"))
    uvicorn.run(app, host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
