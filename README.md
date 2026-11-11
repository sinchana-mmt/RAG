# DigiTrail Known Issues Assistant

On-premise support assistant for **DT-FAQ-001, Revision 01 (05 November 2026)**. It answers only from the official DigiTrail Known Issues FAQ (52 cases). If the screen sentence is not in the FAQ, it returns the escalation protocol instead of guessing.

## How it retrieves

1. **Atomic case chunks** — each Case 01–52 is one unbroken document (scenario, what you see, meaning, steps, pass, escalate).
2. **Hybrid search** — BM25 keyword match + FAISS vector similarity, fused with reciprocal rank fusion. Exact on-screen sentences and `Case NN` lookups are boosted.
3. **Deterministic answers** — default path fills the official response template from the matched case (`temperature=0`, no invented steps). An optional on-prem LLM can copy-format the same retrieved case.

## Run

```powershell
cd C:\Users\mysoreminds\Desktop\RAG
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src\eval_retrieval.py
python src\ask.py "sampling_qty must be greater than zero"
# Always start the UI from the project venv (avoids ModuleNotFoundError):
.\.venv\Scripts\python.exe -m streamlit run src\app.py --server.port 8501
# Or:
.\run.ps1
.\.venv\Scripts\python.exe src\api.py
```

The fetch API listens on `http://127.0.0.1:7010` (port 8000 is already the inward FastAPI). The client keeps calling the gateway at `http://localhost:7002/v1`. Add this on the gateway and proxy `/v1/faq` to the FAQ service:

```
FAQ_SERVICE_URL=http://127.0.0.1:7010
```

```javascript
const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/faq/ask`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${accessToken}`,
  },
  body: JSON.stringify({
    question: "sampling_qty must be greater than zero",
  }),
});
const data = await response.json();
```

Direct check, without the gateway:

```powershell
curl http://127.0.0.1:7010/v1/faq/ask -Method POST -ContentType "application/json" -Body '{"question":"sampling_qty must be greater than zero"}'
```

Optional LLM: copy `.env.example` to `.env`. Use `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`, or the Azure OpenAI deployment already used by inward (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT_NAME`). Leave them empty on the floor PC to keep answers as a direct FAQ template fill. Do not commit Keycloak, storage, SMTP, or OCR secrets.
